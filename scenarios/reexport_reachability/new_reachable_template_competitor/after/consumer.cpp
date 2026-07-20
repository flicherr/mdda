import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] auto result = score(1);
  return static_cast<int>(result);
}
