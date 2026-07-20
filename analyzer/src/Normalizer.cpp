#include "manalyzer/Normalizer.h"
#include "manalyzer/StableId.h"
#include "clang/AST/Attr.h"
#include "clang/AST/DeclCXX.h"
#include "clang/AST/DeclTemplate.h"
#include "clang/AST/PrettyPrinter.h"
#include "llvm/ADT/SmallString.h"
#include "llvm/Support/raw_ostream.h"
#include <cctype>
#include <string>
#include <utility>

namespace manalyzer {

namespace {

const clang::TemplateParameterList *
templateParameters(const clang::NamedDecl *Declaration) {
    if (const auto *Value =
            llvm::dyn_cast<clang::FunctionTemplateDecl>(Declaration)) {
        return Value->getTemplateParameters();
    }
    if (const auto *Value =
            llvm::dyn_cast<clang::ClassTemplateDecl>(Declaration)) {
        return Value->getTemplateParameters();
    }
    if (const auto *Value =
            llvm::dyn_cast<clang::VarTemplateDecl>(Declaration)) {
        return Value->getTemplateParameters();
    }
    if (const auto *Value =
            llvm::dyn_cast<clang::TypeAliasTemplateDecl>(Declaration)) {
        return Value->getTemplateParameters();
    }
    if (const auto *Value = llvm::dyn_cast<clang::ConceptDecl>(Declaration)) {
        return Value->getTemplateParameters();
    }
    return nullptr;
}

std::string templateArgumentText(const clang::TemplateArgument &Argument,
                                 const clang::PrintingPolicy &Policy) {
    std::string Result;
    llvm::raw_string_ostream Stream(Result);
    Argument.print(Policy, Stream, true);
    Stream.flush();
    return Result;
}

} // namespace

DeclarationNormalizer::DeclarationNormalizer(clang::ASTContext &Context)
    : Context(Context), Policy(Context.getLangOpts()) {
    Policy.SuppressScope = false;
    Policy.SuppressTagKeyword = false;
    Policy.PrintAsCanonical = true;
}

std::string
DeclarationNormalizer::collapseWhitespace(llvm::StringRef Text) const {
    std::string Result;
    Result.reserve(Text.size());
    bool PendingSpace = false;
    for (const char Character : Text) {
        if (std::isspace(static_cast<unsigned char>(Character))) {
            PendingSpace = !Result.empty();
            continue;
        }
        if (PendingSpace && !Result.empty()) {
            Result.push_back(' ');
        }
        PendingSpace = false;
        Result.push_back(Character);
    }
    return Result;
}

std::string
DeclarationNormalizer::expressionText(const clang::Expr *Expression) const {
    if (Expression == nullptr) {
        return {};
    }
    std::string Result;
    llvm::raw_string_ostream Stream(Result);
    Expression->printPretty(Stream, nullptr, Policy);
    Stream.flush();
    return collapseWhitespace(Result);
}

std::string
DeclarationNormalizer::statementText(const clang::Stmt *Statement) const {
    if (Statement == nullptr) {
        return {};
    }
    std::string Result;
    llvm::raw_string_ostream Stream(Result);
    Statement->printPretty(Stream, nullptr, Policy);
    Stream.flush();
    return collapseWhitespace(Result);
}

llvm::json::Array
DeclarationNormalizer::attributes(const clang::Decl *Declaration) const {
    llvm::json::Array Result;
    if (Declaration == nullptr) {
        return Result;
    }
    for (const clang::Attr *Attribute : Declaration->attrs()) {
        llvm::json::Object Entry;
        Entry["kind"] = static_cast<int64_t>(Attribute->getKind());
        Entry["implicit"] = Attribute->isImplicit();
        Entry["inherited"] = Attribute->isInherited();
        Result.push_back(std::move(Entry));
    }
    return Result;
}

llvm::json::Object
DeclarationNormalizer::normalize(const clang::NamedDecl *Declaration) const {
    Declaration = canonicalDeclaration(Declaration);
    llvm::json::Object Result;
    Result["kind"] = Declaration->getDeclKindName();
    Result["qualified_name"] = Declaration->getQualifiedNameAsString();
    Result["owning_module"] = owningModuleName(Declaration);
    Result["attributes"] = attributes(Declaration);

    if (const auto *Value = llvm::dyn_cast<clang::ValueDecl>(Declaration)) {
        Result["canonical_type"] = canonicalTypeName(Value->getType(), Context);
    }

    if (const auto *Function =
            llvm::dyn_cast<clang::FunctionDecl>(Declaration)) {
        Result["return_type"] =
            canonicalTypeName(Function->getReturnType(), Context);
        Result["variadic"] = Function->isVariadic();
        Result["constexpr"] = Function->isConstexpr();
        Result["consteval"] = Function->isConsteval();
        Result["inline_specified"] = Function->isInlineSpecified();

        llvm::json::Array Parameters;
        for (const clang::ParmVarDecl *Parameter : Function->parameters()) {
            llvm::json::Object Entry;
            Entry["type"] = canonicalTypeName(Parameter->getType(), Context);
            Entry["pack"] = Parameter->isParameterPack();
            if (Parameter->hasDefaultArg()) {
                Entry["default_argument"] =
                    expressionText(Parameter->getDefaultArg());
            }
            Parameters.push_back(std::move(Entry));
        }
        Result["parameters"] = std::move(Parameters);
        if (const clang::AssociatedConstraint &Requires =
                Function->getTrailingRequiresClause()) {
            Result["trailing_requires"] =
                expressionText(Requires.ConstraintExpr);
        }
        const bool BodyIsInterfaceRelevant =
            Function->isInlineSpecified() || Function->isConstexpr() ||
            Function->getDescribedFunctionTemplate() != nullptr;
        if (BodyIsInterfaceRelevant &&
            Function->doesThisDeclarationHaveABody()) {
            Result["body"] = statementText(Function->getBody());
        }
    }

    if (const auto *Template =
            llvm::dyn_cast<clang::FunctionTemplateDecl>(Declaration)) {
        Result["templated_declaration"] =
            stableId(Template->getTemplatedDecl(), Context);
    }

    if (const clang::TemplateParameterList *Parameters =
            templateParameters(Declaration)) {
        llvm::json::Array Entries;
        for (const clang::NamedDecl *Parameter : *Parameters) {
            llvm::json::Object Entry;
            Entry["kind"] = Parameter->getDeclKindName();
            Entry["name"] = Parameter->getNameAsString();
            if (const auto *Type =
                    llvm::dyn_cast<clang::TemplateTypeParmDecl>(Parameter)) {
                Entry["pack"] = Type->isParameterPack();
                Entry["has_default"] = Type->hasDefaultArgument();
            } else if (const auto *Value =
                           llvm::dyn_cast<clang::NonTypeTemplateParmDecl>(
                               Parameter)) {
                Entry["type"] = canonicalTypeName(Value->getType(), Context);
                Entry["pack"] = Value->isParameterPack();
                Entry["has_default"] = Value->hasDefaultArgument();
            } else if (const auto *Nested =
                           llvm::dyn_cast<clang::TemplateTemplateParmDecl>(
                               Parameter)) {
                Entry["pack"] = Nested->isParameterPack();
                Entry["has_default"] = Nested->hasDefaultArgument();
            }
            Entries.push_back(std::move(Entry));
        }
        Result["template_parameters"] = std::move(Entries);
        if (const clang::Expr *Requires = Parameters->getRequiresClause()) {
            Result["template_requires"] = expressionText(Requires);
        }
    }

    const clang::CXXRecordDecl *Record =
        llvm::dyn_cast<clang::CXXRecordDecl>(Declaration);
    if (const auto *Template =
            llvm::dyn_cast<clang::ClassTemplateDecl>(Declaration)) {
        Record = Template->getTemplatedDecl();
    }
    if (Record != nullptr) {
        if (const clang::CXXRecordDecl *Definition = Record->getDefinition()) {
            llvm::json::Array Bases;
            for (const clang::CXXBaseSpecifier &Base : Definition->bases()) {
                llvm::json::Object Entry;
                Entry["type"] = canonicalTypeName(Base.getType(), Context);
                Entry["virtual"] = Base.isVirtual();
                Entry["access"] =
                    static_cast<int64_t>(Base.getAccessSpecifier());
                Bases.push_back(std::move(Entry));
            }
            Result["bases"] = std::move(Bases);

            llvm::json::Array Fields;
            for (const clang::FieldDecl *Field : Definition->fields()) {
                llvm::json::Object Entry;
                Entry["name"] = Field->getNameAsString();
                Entry["type"] = canonicalTypeName(Field->getType(), Context);
                Entry["mutable"] = Field->isMutable();
                Entry["access"] = static_cast<int64_t>(Field->getAccess());
                if (Field->hasInClassInitializer()) {
                    Entry["initializer"] =
                        expressionText(Field->getInClassInitializer());
                }
                Fields.push_back(std::move(Entry));
            }
            Result["fields"] = std::move(Fields);

            llvm::json::Array Methods;
            for (const clang::CXXMethodDecl *Method : Definition->methods()) {
                // Implicit special members are materialized on demand.
                // Including them makes an imported class normalize differently
                // in provider and consumer scans even when its source
                // declaration is identical.
                if (Method->isImplicit()) {
                    continue;
                }
                llvm::json::Object Entry;
                Entry["name"] = Method->getNameAsString();
                Entry["type"] = canonicalTypeName(Method->getType(), Context);
                Entry["static"] = Method->isStatic();
                Entry["virtual"] = Method->isVirtual();
                Methods.push_back(std::move(Entry));
            }
            Result["methods"] = std::move(Methods);
        }
    }

    if (const auto *Enumeration =
            llvm::dyn_cast<clang::EnumDecl>(Declaration)) {
        Result["scoped"] = Enumeration->isScoped();
        Result["underlying_type"] =
            canonicalTypeName(Enumeration->getIntegerType(), Context);
        llvm::json::Array Enumerators;
        for (const clang::EnumConstantDecl *Enumerator :
             Enumeration->enumerators()) {
            llvm::SmallString<32> Text;
            Enumerator->getInitVal().toString(Text, 10);
            llvm::json::Object Entry;
            Entry["name"] = Enumerator->getNameAsString();
            Entry["value"] = std::string(Text);
            Enumerators.push_back(std::move(Entry));
        }
        Result["enumerators"] = std::move(Enumerators);
    }

    if (const auto *Typedef =
            llvm::dyn_cast<clang::TypedefNameDecl>(Declaration)) {
        Result["underlying_type"] =
            canonicalTypeName(Typedef->getUnderlyingType(), Context);
    }
    if (const auto *Variable = llvm::dyn_cast<clang::VarDecl>(Declaration)) {
        Result["constexpr"] = Variable->isConstexpr();
        Result["inline"] = Variable->isInline();
        if ((Variable->isConstexpr() || Variable->isInline()) &&
            Variable->hasInit()) {
            Result["initializer"] = expressionText(Variable->getInit());
        }
    }

    if (const auto *Concept = llvm::dyn_cast<clang::ConceptDecl>(Declaration)) {
        Result["constraint_expression"] =
            expressionText(Concept->getConstraintExpr());
    }
    if (const auto *Using = llvm::dyn_cast<clang::UsingDecl>(Declaration)) {
        llvm::json::Array Targets;
        for (const clang::UsingShadowDecl *Shadow : Using->shadows()) {
            if (const clang::NamedDecl *Target = Shadow->getTargetDecl()) {
                Targets.push_back(stableId(Target, Context));
            }
        }
        Result["using_targets"] = std::move(Targets);
    }

    if (const auto *Specialization =
            llvm::dyn_cast<clang::ClassTemplateSpecializationDecl>(
                Declaration)) {
        llvm::json::Array Arguments;
        for (const clang::TemplateArgument &Argument :
             Specialization->getTemplateArgs().asArray()) {
            Arguments.push_back(templateArgumentText(Argument, Policy));
        }
        Result["template_arguments"] = std::move(Arguments);
    }

    if (const auto *Guide =
            llvm::dyn_cast<clang::CXXDeductionGuideDecl>(Declaration)) {
        if (const clang::TemplateDecl *Template = Guide->getDeducedTemplate()) {
            Result["deduced_template"] = stableId(Template, Context);
        }
        Result["explicit"] = Guide->isExplicit();
    }

    return Result;
}

llvm::json::Object
DeclarationNormalizer::record(const clang::NamedDecl *Declaration) const {
    Declaration = canonicalDeclaration(Declaration);
    llvm::json::Object Result = declarationIdentity(Declaration, Context);
    Result["exported"] = Declaration->isInExportDeclContext();
    Result["implicit"] = Declaration->isImplicit();
    Result["normalized"] = normalize(Declaration);
    return Result;
}

} // namespace manalyzer
