import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] long result = Number{};
  return static_cast<int>(result);
}
