#ifndef MANALYZER_OPTIONS_H
#define MANALYZER_OPTIONS_H

#include <set>
#include <string>

namespace manalyzer {

enum class AnalysisMode { Provider, Consumer };

struct AnalyzerOptions {
    AnalysisMode Mode = AnalysisMode::Provider;
    std::string OutputPath;
    std::string LogicalModule;
    std::string ProbeId;
    std::set<std::string> TrackedModules;
};

} // namespace manalyzer

#endif // MANALYZER_OPTIONS_H
