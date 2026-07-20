#ifndef MANALYZER_ANALYZER_H
#define MANALYZER_ANALYZER_H

#include "manalyzer/Options.h"
#include "clang/Frontend/FrontendAction.h"
#include "clang/Tooling/Tooling.h"
#include <memory>

namespace manalyzer {

class AnalyzerAction final : public clang::ASTFrontendAction {
  public:
    explicit AnalyzerAction(AnalyzerOptions Options);

    std::unique_ptr<clang::ASTConsumer>
    CreateASTConsumer(clang::CompilerInstance &Compiler,
                      llvm::StringRef InputFile) override;

  private:
    AnalyzerOptions Options;
};

class AnalyzerActionFactory final
    : public clang::tooling::FrontendActionFactory {
  public:
    explicit AnalyzerActionFactory(AnalyzerOptions Options);

    std::unique_ptr<clang::FrontendAction> create() override;

  private:
    AnalyzerOptions Options;
};

} // namespace manalyzer

#endif // MANALYZER_ANALYZER_H
