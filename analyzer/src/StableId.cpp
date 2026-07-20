#include "manalyzer/StableId.h"
#include "clang/AST/ASTContext.h"
#include "clang/AST/DeclCXX.h"
#include "clang/AST/DeclTemplate.h"
#include "clang/AST/PrettyPrinter.h"
#include "clang/Basic/Module.h"
#include "clang/Index/USRGeneration.h"
#include "llvm/ADT/SmallString.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Support/raw_ostream.h"
#include <cctype>

namespace manalyzer {

namespace {

std::string collapseWhitespace(llvm::StringRef Text) {
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

} // namespace

const clang::NamedDecl *
canonicalDeclaration(const clang::NamedDecl *Declaration) {
    if (Declaration == nullptr) {
        return nullptr;
    }
    if (const auto *Record =
            llvm::dyn_cast<clang::CXXRecordDecl>(Declaration)) {
        if (const clang::ClassTemplateDecl *Template =
                Record->getDescribedClassTemplate()) {
            return Template->getCanonicalDecl();
        }
    }
    return llvm::cast<clang::NamedDecl>(Declaration->getCanonicalDecl());
}

std::string owningModuleName(const clang::Decl *Declaration) {
    if (Declaration == nullptr) {
        return {};
    }
    const clang::Module *Module = Declaration->getOwningModule();
    if (Module == nullptr) {
        return {};
    }
    return Module->getFullModuleName();
}

std::string canonicalTypeName(clang::QualType Type,
                              const clang::ASTContext &Context) {
    if (Type.isNull()) {
        return {};
    }
    clang::PrintingPolicy Policy(Context.getLangOpts());
    Policy.SuppressTagKeyword = false;
    Policy.SuppressScope = false;
    Policy.PrintAsCanonical = true;
    return Type.getCanonicalType().getAsString(Policy);
}

std::string declarationUsr(const clang::NamedDecl *Declaration) {
    Declaration = canonicalDeclaration(Declaration);
    if (Declaration == nullptr) {
        return {};
    }
    llvm::SmallString<256> Buffer;
    if (clang::index::generateUSRForDecl(Declaration, Buffer)) {
        return {};
    }
    return std::string(Buffer);
}

static unsigned templateArity(const clang::NamedDecl *Declaration) {
    if (const auto *Function =
            llvm::dyn_cast<clang::FunctionTemplateDecl>(Declaration)) {
        return Function->getTemplateParameters()->size();
    }
    if (const auto *Class =
            llvm::dyn_cast<clang::ClassTemplateDecl>(Declaration)) {
        return Class->getTemplateParameters()->size();
    }
    if (const auto *Variable =
            llvm::dyn_cast<clang::VarTemplateDecl>(Declaration)) {
        return Variable->getTemplateParameters()->size();
    }
    if (const auto *Alias =
            llvm::dyn_cast<clang::TypeAliasTemplateDecl>(Declaration)) {
        return Alias->getTemplateParameters()->size();
    }
    if (const auto *Concept = llvm::dyn_cast<clang::ConceptDecl>(Declaration)) {
        return Concept->getTemplateParameters()->size();
    }
    return 0;
}

static std::string declarationType(const clang::NamedDecl *Declaration,
                                   const clang::ASTContext &Context) {
    if (const auto *Template =
            llvm::dyn_cast<clang::FunctionTemplateDecl>(Declaration)) {
        return canonicalTypeName(Template->getTemplatedDecl()->getType(),
                                 Context);
    }
    if (const auto *Value = llvm::dyn_cast<clang::ValueDecl>(Declaration)) {
        return canonicalTypeName(Value->getType(), Context);
    }
    if (const auto *Typedef =
            llvm::dyn_cast<clang::TypedefNameDecl>(Declaration)) {
        return canonicalTypeName(Typedef->getUnderlyingType(), Context);
    }
    return {};
}

static std::string declarationConstraint(const clang::NamedDecl *Declaration,
                                         const clang::ASTContext &Context) {
    const clang::Expr *Constraint = nullptr;
    if (const auto *Template =
            llvm::dyn_cast<clang::FunctionTemplateDecl>(Declaration)) {
        Constraint = Template->getTemplateParameters()->getRequiresClause();
        if (Constraint == nullptr) {
            if (const clang::AssociatedConstraint &Trailing =
                    Template->getTemplatedDecl()->getTrailingRequiresClause()) {
                Constraint = Trailing.ConstraintExpr;
            }
        }
    } else if (const auto *Function =
                   llvm::dyn_cast<clang::FunctionDecl>(Declaration)) {
        if (const clang::AssociatedConstraint &Trailing =
                Function->getTrailingRequiresClause()) {
            Constraint = Trailing.ConstraintExpr;
        }
    }
    if (Constraint == nullptr) {
        return {};
    }

    clang::PrintingPolicy Policy(Context.getLangOpts());
    Policy.SuppressScope = false;
    Policy.SuppressTagKeyword = false;
    Policy.PrintAsCanonical = true;
    std::string Result;
    llvm::raw_string_ostream Stream(Result);
    Constraint->printPretty(Stream, nullptr, Policy);
    Stream.flush();
    return collapseWhitespace(Result);
}

std::string structuralKey(const clang::NamedDecl *Declaration,
                          const clang::ASTContext &Context) {
    Declaration = canonicalDeclaration(Declaration);
    if (Declaration == nullptr) {
        return {};
    }
    std::string Result;
    llvm::raw_string_ostream Stream(Result);
    Stream << owningModuleName(Declaration) << '|'
           << Declaration->getDeclKindName() << '|'
           << Declaration->getQualifiedNameAsString() << '|'
           << declarationType(Declaration, Context) << '|'
           << templateArity(Declaration) << '|'
           << declarationConstraint(Declaration, Context);
    Stream.flush();
    return Result;
}

std::string stableId(const clang::NamedDecl *Declaration,
                     const clang::ASTContext &Context) {
    const std::string Usr = declarationUsr(Declaration);
    if (!Usr.empty()) {
        return "usr:" + Usr;
    }
    return "key:" + structuralKey(Declaration, Context);
}

llvm::json::Object declarationIdentity(const clang::NamedDecl *Declaration,
                                       const clang::ASTContext &Context) {
    Declaration = canonicalDeclaration(Declaration);
    llvm::json::Object Result;
    Result["stable_id"] = stableId(Declaration, Context);
    Result["usr"] = declarationUsr(Declaration);
    Result["structural_key"] = structuralKey(Declaration, Context);
    Result["kind"] =
        Declaration != nullptr ? Declaration->getDeclKindName() : "";
    Result["qualified_name"] =
        Declaration != nullptr ? Declaration->getQualifiedNameAsString() : "";
    Result["owning_module"] = owningModuleName(Declaration);
    return Result;
}

} // namespace manalyzer
