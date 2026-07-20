#include "manalyzer/Analyzer.h"
#include "manalyzer/Options.h"
#include "clang/Basic/Version.h"
#include "clang/Tooling/CommonOptionsParser.h"
#include "clang/Tooling/Tooling.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/Error.h"
#include "llvm/Support/raw_ostream.h"
#include <set>
#include <string>

namespace {

llvm::cl::OptionCategory Category("manalyzer options");

llvm::cl::opt<std::string>
    Mode("mode", llvm::cl::desc("Analysis mode: provider or consumer"),
         llvm::cl::value_desc("mode"), llvm::cl::Required,
         llvm::cl::cat(Category));

llvm::cl::opt<std::string> Output("output",
                                  llvm::cl::desc("Destination JSON file"),
                                  llvm::cl::value_desc("path"),
                                  llvm::cl::Required, llvm::cl::cat(Category));

llvm::cl::opt<std::string> LogicalModule(
    "logical-module", llvm::cl::desc("Logical module name for provider scans"),
    llvm::cl::value_desc("name"), llvm::cl::init(""), llvm::cl::cat(Category));

llvm::cl::opt<std::string> ProbeId(
    "probe-id", llvm::cl::desc("Requested manalyzer_probe annotation id"),
    llvm::cl::value_desc("id"), llvm::cl::init(""), llvm::cl::cat(Category));

llvm::cl::list<std::string>
    TrackedModules("tracked-module",
                   llvm::cl::desc("Module whose declarations count as uses"),
                   llvm::cl::ZeroOrMore, llvm::cl::cat(Category));

} // namespace

int main(int argc, const char **argv) {
    if (argc == 2 && llvm::StringRef(argv[1]) == "--version") {
        llvm::outs() << "manalyzer " MANALYZER_VERSION "\n"
                     << clang::getClangFullVersion() << '\n';
        return 0;
    }

    auto Parser =
        clang::tooling::CommonOptionsParser::create(argc, argv, Category);
    if (!Parser) {
        llvm::errs() << llvm::toString(Parser.takeError()) << '\n';
        return 2;
    }

    manalyzer::AnalyzerOptions Options;
    if (Mode == "provider") {
        Options.Mode = manalyzer::AnalysisMode::Provider;
    } else if (Mode == "consumer") {
        Options.Mode = manalyzer::AnalysisMode::Consumer;
    } else {
        llvm::errs() << "manalyzer: --mode must be provider or consumer\n";
        return 2;
    }
    Options.OutputPath = Output;
    Options.LogicalModule = LogicalModule;
    Options.ProbeId = ProbeId;
    Options.TrackedModules =
        std::set<std::string>(TrackedModules.begin(), TrackedModules.end());

    clang::tooling::ClangTool Tool(Parser->getCompilations(),
                                   Parser->getSourcePathList());
    manalyzer::AnalyzerActionFactory Factory(std::move(Options));
    return Tool.run(&Factory);
}
