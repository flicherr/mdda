#ifndef MANALYZER_STABLEID_H
#define MANALYZER_STABLEID_H

#include "clang/AST/Decl.h"
#include "clang/AST/Type.h"
#include "llvm/Support/JSON.h"
#include <string>

namespace manalyzer {

// Clang exposes a class template and its templated CXXRecordDecl as distinct
// AST nodes.  They can share a USR, and the node encountered first changed
// between Clang releases.  Treat both nodes as one semantic dependency entity
// so that fingerprints do not depend on traversal order.
const clang::NamedDecl *
canonicalDeclaration(const clang::NamedDecl *Declaration);
std::string owningModuleName(const clang::Decl *Declaration);
std::string canonicalTypeName(clang::QualType Type,
                              const clang::ASTContext &Context);
std::string declarationUsr(const clang::NamedDecl *Declaration);
std::string structuralKey(const clang::NamedDecl *Declaration,
                          const clang::ASTContext &Context);
std::string stableId(const clang::NamedDecl *Declaration,
                     const clang::ASTContext &Context);
llvm::json::Object declarationIdentity(const clang::NamedDecl *Declaration,
                                       const clang::ASTContext &Context);

} // namespace manalyzer

#endif // MANALYZER_STABLEID_H
