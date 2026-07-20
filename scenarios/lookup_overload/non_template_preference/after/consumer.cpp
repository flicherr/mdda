import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] auto result = choose(1);
  return static_cast<int>(result);
}
