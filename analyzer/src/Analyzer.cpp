#include "manalyzer/Analyzer.h"
#include "manalyzer/Normalizer.h"
#include "manalyzer/StableId.h"
#include "clang/AST/ASTConsumer.h"
#include "clang/AST/Attr.h"
#include "clang/AST/DeclCXX.h"
#include "clang/AST/DeclTemplate.h"
#include "clang/AST/ExprConcepts.h"
#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/AST/TypeLoc.h"
#include "clang/Basic/Module.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Basic/Version.h"
#include "clang/Frontend/CompilerInstance.h"
#include "llvm/ADT/SmallVector.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/FormatVariadic.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/Path.h"
#include "llvm/Support/raw_ostream.h"
#include <map>
#include <memory>
#include <set>
#include <string>
#include <system_error>
#include <utility>
#include <vector>

namespace manalyzer {

namespace {

bool isMainFileDeclaration(const clang::Decl *Declaration,
                           const clang::SourceManager &Sources) {
    if (Declaration == nullptr || Declaration->getLocation().isInvalid()) {
        return false;
    }
    return Sources.isWrittenInMainFile(
        Sources.getExpansionLoc(Declaration->getLocation()));
}

bool isExportedDeclaration(const clang::NamedDecl *Declaration) {
    if (Declaration->isInExportDeclContext()) {
        return true;
    }
    const clang::DeclContext *Context = Declaration->getDeclContext();
    while (Context != nullptr && !Context->isTranslationUnit()) {
        const clang::Decl *Parent = clang::Decl::castFromDeclContext(Context);
        if (Parent != nullptr && Parent->isInExportDeclContext()) {
            return true;
        }
        Context = Context->getParent();
    }
    return false;
}

const clang::NamedDecl *
dependencyRepresentative(const clang::NamedDecl *Value) {
    if (Value == nullptr) {
        return nullptr;
    }
    if (const auto *Method = llvm::dyn_cast<clang::CXXMethodDecl>(Value)) {
        if (const auto *SpecializedParent =
                llvm::dyn_cast<clang::ClassTemplateSpecializationDecl>(
                    Method->getParent())) {
            return SpecializedParent->getSpecializedTemplate();
        }
    }
    if (const auto *Function = llvm::dyn_cast<clang::FunctionDecl>(Value)) {
        if (const clang::FunctionTemplateDecl *Primary =
                Function->getPrimaryTemplate()) {
            return Primary;
        }
    }
    if (const auto *Class =
            llvm::dyn_cast<clang::ClassTemplateSpecializationDecl>(Value)) {
        return Class->getSpecializedTemplate();
    }
    if (const auto *Variable =
            llvm::dyn_cast<clang::VarTemplateSpecializationDecl>(Value)) {
        return Variable->getSpecializedTemplate();
    }
    return canonicalDeclaration(Value);
}

const clang::NamedDecl *selectedDeclaration(const clang::Expr *Expression) {
    if (Expression == nullptr) {
        return nullptr;
    }
    const clang::Expr *Core = Expression->IgnoreParenImpCasts();
    if (const auto *Call = llvm::dyn_cast<clang::CallExpr>(Core)) {
        if (const clang::FunctionDecl *Callee = Call->getDirectCallee()) {
            return Callee;
        }
    }
    if (const auto *Construction =
            llvm::dyn_cast<clang::CXXConstructExpr>(Core)) {
        return Construction->getConstructor();
    }
    if (const auto *Reference = llvm::dyn_cast<clang::DeclRefExpr>(Core)) {
        return Reference->getDecl();
    }
    if (const auto *Member = llvm::dyn_cast<clang::MemberExpr>(Core)) {
        return Member->getMemberDecl();
    }
    for (const clang::Stmt *Child : Core->children()) {
        if (const auto *ChildExpression =
                llvm::dyn_cast_or_null<clang::Expr>(Child)) {
            if (const clang::NamedDecl *Found =
                    selectedDeclaration(ChildExpression)) {
                return Found;
            }
        }
    }
    return nullptr;
}

llvm::json::Object
selectedDeclarationRecord(const clang::NamedDecl *Declaration,
                          DeclarationNormalizer &Normalizer) {
    llvm::json::Object Record = Normalizer.record(Declaration);
    if (const auto *Function =
            llvm::dyn_cast_or_null<clang::FunctionDecl>(Declaration)) {
        // A selected function-template specialization may have the same Clang
        // USR as another constrained overload. Preserve the primary template
        // and its associated constraints so the reference observation can
        // distinguish both selections.
        if (const clang::FunctionTemplateDecl *Primary =
                Function->getPrimaryTemplate()) {
            Record["primary_template"] = Normalizer.record(Primary);
        }
    }
    return Record;
}

const clang::NamedDecl *selectedSpecialization(clang::QualType Type) {
    if (Type.isNull()) {
        return nullptr;
    }
    const clang::Type *Canonical = Type.getCanonicalType().getTypePtrOrNull();
    if (Canonical == nullptr) {
        return nullptr;
    }
    if (const auto *RecordType = Canonical->getAs<clang::RecordType>()) {
        if (const auto *Specialization =
                llvm::dyn_cast<clang::ClassTemplateSpecializationDecl>(
                    RecordType->getDecl())) {
            return Specialization;
        }
    }
    return nullptr;
}

llvm::json::Object locationRecord(clang::SourceLocation Location,
                                  const clang::SourceManager &Sources) {
    llvm::json::Object Result;
    const clang::PresumedLoc Presumed = Sources.getPresumedLoc(Location);
    if (Presumed.isInvalid()) {
        return Result;
    }
    Result["file"] = llvm::sys::path::filename(Presumed.getFilename()).str();
    Result["line"] = static_cast<int64_t>(Presumed.getLine());
    Result["column"] = static_cast<int64_t>(Presumed.getColumn());
    return Result;
}

struct UseAccumulator {
    llvm::json::Object Declaration;
    std::set<std::string> Kinds;
    llvm::json::Array Locations;
};

class SemanticVisitor final
    : public clang::RecursiveASTVisitor<SemanticVisitor> {
  public:
    SemanticVisitor(clang::ASTContext &Context, const AnalyzerOptions &Options)
        : Context(Context), Sources(Context.getSourceManager()),
          Options(Options), Normalizer(Context) {}

    bool shouldVisitTemplateInstantiations() const { return true; }
    bool shouldVisitImplicitCode() const { return true; }

    bool VisitImportDecl(clang::ImportDecl *Declaration) {
        if (Options.Mode != AnalysisMode::Provider ||
            !isMainFileDeclaration(Declaration, Sources)) {
            return true;
        }
        const clang::Module *Imported = Declaration->getImportedModule();
        if (Imported == nullptr) {
            return true;
        }
        const std::string Name = Imported->getFullModuleName();
        bool Exported = Declaration->isInExportDeclContext();
        // Clang represents `export import M;` as a plain ImportDecl and records
        // the re-export on the current named Module rather than wrapping the
        // ImportDecl in an ExportDecl. Consult that semantic export set as
        // well.
        if (!Exported) {
            if (const clang::Module *Current =
                    Context.getCurrentNamedModule()) {
                llvm::SmallVector<clang::Module *, 4> Reexported;
                Current->getExportedModules(Reexported);
                for (const clang::Module *Candidate : Reexported) {
                    if (Candidate == Imported ||
                        Candidate->getFullModuleName() ==
                            Imported->getFullModuleName()) {
                        Exported = true;
                        break;
                    }
                }
            }
        }
        Imports[Name] = Imports[Name] || Exported;
        return true;
    }

    bool VisitNamedDecl(clang::NamedDecl *Declaration) {
        if (Options.Mode != AnalysisMode::Provider ||
            Declaration->isImplicit() ||
            !isMainFileDeclaration(Declaration, Sources) ||
            !isExportedDeclaration(Declaration)) {
            return true;
        }
        if (llvm::isa<clang::NamespaceDecl, clang::UsingShadowDecl,
                      clang::TemplateTypeParmDecl,
                      clang::NonTypeTemplateParmDecl,
                      clang::TemplateTemplateParmDecl, clang::ParmVarDecl,
                      clang::EnumConstantDecl>(Declaration)) {
            return true;
        }
        if (Declaration->getDeclContext()->isFunctionOrMethod()) {
            return true;
        }

        addProviderDeclaration(Declaration);

        // An exported using-declaration exposes its targets even when their
        // original declarations are not themselves lexically under export.
        if (const auto *Using = llvm::dyn_cast<clang::UsingDecl>(Declaration)) {
            for (const clang::UsingShadowDecl *Shadow : Using->shadows()) {
                const clang::NamedDecl *Target = Shadow->getTargetDecl();
                if (Target == nullptr) {
                    continue;
                }
                addProviderDeclaration(Target);
            }
        }
        return true;
    }

    bool VisitDeclRefExpr(clang::DeclRefExpr *Expression) {
        if (Options.Mode == AnalysisMode::Consumer) {
            addUse(Expression->getDecl(), "decl_ref", Expression->getExprLoc());
        }
        return true;
    }

    bool VisitMemberExpr(clang::MemberExpr *Expression) {
        if (Options.Mode == AnalysisMode::Consumer) {
            addUse(Expression->getMemberDecl(), "member_ref",
                   Expression->getExprLoc());
        }
        return true;
    }

    bool VisitCallExpr(clang::CallExpr *Expression) {
        if (Options.Mode == AnalysisMode::Consumer) {
            addUse(Expression->getDirectCallee(), "direct_callee",
                   Expression->getExprLoc());
        }
        return true;
    }

    bool VisitCXXConstructExpr(clang::CXXConstructExpr *Expression) {
        if (Options.Mode != AnalysisMode::Consumer) {
            return true;
        }
        addUse(Expression->getConstructor(), "constructor",
               Expression->getExprLoc());
        if (Expression->getConstructor() != nullptr) {
            addUse(Expression->getConstructor()->getParent(),
                   "constructed_type", Expression->getExprLoc());
        }
        return true;
    }

    bool VisitConceptSpecializationExpr(
        clang::ConceptSpecializationExpr *Expression) {
        if (Options.Mode == AnalysisMode::Consumer) {
            addUse(Expression->getNamedConcept(), "concept_specialization",
                   Expression->getExprLoc());
        }
        return true;
    }

    bool VisitTypeLoc(clang::TypeLoc Location) {
        if (Options.Mode != AnalysisMode::Consumer || Location.isNull()) {
            return true;
        }
        const clang::Type *Type = Location.getTypePtr();
        if (const auto *Tag = Type->getAs<clang::TagType>()) {
            addUse(Tag->getDecl(), "type_loc", Location.getBeginLoc());
        }
        if (const auto *Typedef = Type->getAs<clang::TypedefType>()) {
            addUse(Typedef->getDecl(), "type_loc", Location.getBeginLoc());
        }
        if (const auto *Specialization =
                Type->getAs<clang::TemplateSpecializationType>()) {
            if (clang::TemplateDecl *Template =
                    Specialization->getTemplateName().getAsTemplateDecl()) {
                addUse(Template, "template_type_loc", Location.getBeginLoc());
            }
        }
        return true;
    }

    bool VisitVarDecl(clang::VarDecl *Declaration) {
        if (Options.Mode != AnalysisMode::Consumer ||
            !isMainFileDeclaration(Declaration, Sources)) {
            return true;
        }
        for (const clang::AnnotateAttr *Annotation :
             Declaration->specific_attrs<clang::AnnotateAttr>()) {
            llvm::StringRef Text = Annotation->getAnnotation();
            if (!Text.consume_front("manalyzer_probe:")) {
                continue;
            }
            if (!Options.ProbeId.empty() && Text != Options.ProbeId) {
                continue;
            }
            addProbe(Text.str(), Declaration);
        }
        return true;
    }

    llvm::json::Array takeDeclarations() {
        llvm::json::Array Result;
        for (auto &[Identity, Records] : Declarations) {
            (void)Identity;
            for (llvm::json::Object &Record : Records) {
                Result.push_back(std::move(Record));
            }
        }
        return Result;
    }

    llvm::json::Array takeImports() {
        llvm::json::Array Result;
        for (const auto &[Name, Exported] : Imports) {
            llvm::json::Object Entry;
            Entry["module"] = Name;
            Entry["exported"] = Exported;
            Result.push_back(std::move(Entry));
        }
        return Result;
    }

    llvm::json::Array takeUses() {
        llvm::json::Array Result;
        for (auto &[StorageKey, Use] : Uses) {
            llvm::json::Object Entry;
            if (auto StableId = Use.Declaration.getString("stable_id")) {
                Entry["identity"] = StableId->str();
            } else {
                Entry["identity"] = StorageKey;
            }
            Entry["declaration"] = std::move(Use.Declaration);
            llvm::json::Array Kinds;
            for (const std::string &Kind : Use.Kinds) {
                Kinds.push_back(Kind);
            }
            Entry["usage_kinds"] = std::move(Kinds);
            Entry["locations"] = std::move(Use.Locations);
            Result.push_back(std::move(Entry));
        }
        return Result;
    }

    llvm::json::Array takeProbes() {
        llvm::json::Array Result;
        for (llvm::json::Object &Probe : Probes) {
            Result.push_back(std::move(Probe));
        }
        return Result;
    }

  private:
    void addProviderDeclaration(const clang::NamedDecl *Declaration) {
        const clang::NamedDecl *Canonical = canonicalDeclaration(Declaration);
        if (Canonical == nullptr ||
            !SeenDeclarations.insert(Canonical).second) {
            return;
        }

        llvm::json::Object Record = Normalizer.record(Canonical);
        if (owningModuleName(Canonical).empty() &&
            !Options.LogicalModule.empty()) {
            Record["owning_module"] = Options.LogicalModule;
            if (llvm::json::Object *Normalized =
                    Record.getObject("normalized")) {
                (*Normalized)["owning_module"] = Options.LogicalModule;
            }
        }
        Record["exported"] = true;
        Declarations[stableId(Canonical, Context)].push_back(std::move(Record));
    }

    void addUse(const clang::NamedDecl *Raw, llvm::StringRef Kind,
                clang::SourceLocation Location) {
        if (Raw == nullptr || Raw->isImplicit()) {
            return;
        }
        if (llvm::isa<clang::ParmVarDecl>(Raw) ||
            Raw->getDeclContext()->isFunctionOrMethod()) {
            return;
        }

        const clang::NamedDecl *Declaration = dependencyRepresentative(Raw);
        if (Declaration == nullptr) {
            return;
        }
        const std::string Module = owningModuleName(Declaration);
        if (Module.empty()) {
            return;
        }
        if (!Options.TrackedModules.empty() &&
            !Options.TrackedModules.contains(Module)) {
            return;
        }
        const std::string Identity = stableId(Declaration, Context);
        const std::string StorageKey =
            Identity + '\n' + structuralKey(Declaration, Context);
        auto Iterator = Uses.find(StorageKey);
        if (Iterator == Uses.end()) {
            UseAccumulator NewUse{Normalizer.record(Declaration), {}, {}};
            Iterator = Uses.try_emplace(StorageKey, std::move(NewUse)).first;
        }
        Iterator->second.Kinds.insert(Kind.str());
        Iterator->second.Locations.push_back(locationRecord(Location, Sources));
    }

    void addProbe(const std::string &Id, const clang::VarDecl *Declaration) {
        llvm::json::Object Probe;
        Probe["id"] = Id;
        Probe["location"] = locationRecord(Declaration->getLocation(), Sources);
        Probe["deduced_type"] =
            canonicalTypeName(Declaration->getType(), Context);
        const clang::Expr *Initializer = Declaration->getInit();
        if (Initializer != nullptr) {
            Probe["expression_type"] =
                canonicalTypeName(Initializer->getType(), Context);
            Probe["expression"] = Normalizer.expressionText(Initializer);
            if (const clang::NamedDecl *Selected =
                    selectedDeclaration(Initializer)) {
                Probe["selected_declaration"] =
                    selectedDeclarationRecord(Selected, Normalizer);
            }
            if (const clang::NamedDecl *Specialization =
                    selectedSpecialization(Declaration->getType())) {
                Probe["selected_specialization"] =
                    Normalizer.record(Specialization);
            }

            clang::Expr::EvalResult Evaluation;
            if (Initializer->EvaluateAsInt(Evaluation, Context)) {
                const llvm::APSInt &Integer = Evaluation.Val.getInt();
                if (Declaration->getType()->isBooleanType()) {
                    Probe["constant_value"] = Integer.getBoolValue();
                } else {
                    llvm::SmallString<32> Text;
                    Integer.toString(Text, 10);
                    Probe["constant_value"] = std::string(Text);
                }
            }
        }
        Probes.push_back(std::move(Probe));
    }

    clang::ASTContext &Context;
    clang::SourceManager &Sources;
    const AnalyzerOptions &Options;
    DeclarationNormalizer Normalizer;
    std::map<std::string, std::vector<llvm::json::Object>> Declarations;
    std::set<const clang::NamedDecl *> SeenDeclarations;
    std::map<std::string, bool> Imports;
    std::map<std::string, UseAccumulator> Uses;
    std::vector<llvm::json::Object> Probes;
};

class AnalyzerConsumer final : public clang::ASTConsumer {
  public:
    AnalyzerConsumer(clang::ASTContext &Context, AnalyzerOptions Options)
        : Context(Context), Options(std::move(Options)),
          Visitor(Context, this->Options) {}

    void HandleTranslationUnit(clang::ASTContext &TranslationUnit) override {
        Visitor.TraverseDecl(TranslationUnit.getTranslationUnitDecl());

        llvm::json::Object Result;
        Result["schema_version"] = 1;
        Result["mode"] =
            Options.Mode == AnalysisMode::Provider ? "provider" : "consumer";
        Result["logical_module"] = Options.LogicalModule;
        Result["probe_request"] = Options.ProbeId;
        Result["source"] =
            Context.getSourceManager()
                .getFilename(Context.getSourceManager().getLocForStartOfFile(
                    Context.getSourceManager().getMainFileID()))
                .str();
        Result["had_errors"] = Context.getDiagnostics().hasErrorOccurred();
        llvm::json::Object Tool;
        Tool["name"] = "manalyzer";
        Tool["version"] = MANALYZER_VERSION;
        Tool["clang"] = clang::getClangFullVersion();
        Result["tool"] = std::move(Tool);
        Result["declarations"] = Visitor.takeDeclarations();
        Result["imports"] = Visitor.takeImports();
        Result["uses"] = Visitor.takeUses();
        Result["probes"] = Visitor.takeProbes();

        std::error_code Error;
        llvm::raw_fd_ostream Output(Options.OutputPath, Error,
                                    llvm::sys::fs::OF_Text);
        if (Error) {
            llvm::errs() << "manalyzer: cannot write " << Options.OutputPath
                         << ": " << Error.message() << '\n';
            return;
        }
        Output << llvm::formatv("{0:2}\n",
                                llvm::json::Value(std::move(Result)));
    }

  private:
    clang::ASTContext &Context;
    AnalyzerOptions Options;
    SemanticVisitor Visitor;
};

} // namespace

AnalyzerAction::AnalyzerAction(AnalyzerOptions Options)
    : Options(std::move(Options)) {}

std::unique_ptr<clang::ASTConsumer>
AnalyzerAction::CreateASTConsumer(clang::CompilerInstance &Compiler,
                                  llvm::StringRef InputFile) {
    (void)InputFile;
    return std::make_unique<AnalyzerConsumer>(Compiler.getASTContext(),
                                              Options);
}

AnalyzerActionFactory::AnalyzerActionFactory(AnalyzerOptions Options)
    : Options(std::move(Options)) {}

std::unique_ptr<clang::FrontendAction> AnalyzerActionFactory::create() {
    return std::make_unique<AnalyzerAction>(Options);
}

} // namespace manalyzer
