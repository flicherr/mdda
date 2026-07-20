#ifndef MANALYZER_NORMALIZER_H
#define MANALYZER_NORMALIZER_H

#include "clang/AST/ASTContext.h"
#include "clang/AST/Decl.h"
#include "clang/AST/Expr.h"
#include "llvm/Support/JSON.h"
#include <string>

namespace manalyzer {

class DeclarationNormalizer {
  public:
    explicit DeclarationNormalizer(clang::ASTContext &Context);

    llvm::json::Object record(const clang::NamedDecl *Declaration) const;
    std::string expressionText(const clang::Expr *Expression) const;
    std::string statementText(const clang::Stmt *Statement) const;

  private:
    llvm::json::Object normalize(const clang::NamedDecl *Declaration) const;
    llvm::json::Array attributes(const clang::Decl *Declaration) const;
    std::string collapseWhitespace(llvm::StringRef Text) const;

    clang::ASTContext &Context;
    clang::PrintingPolicy Policy;
};

} // namespace manalyzer

#endif // MANALYZER_NORMALIZER_H
