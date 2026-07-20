import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] auto result = rank(1);
  return static_cast<int>(result);
}
