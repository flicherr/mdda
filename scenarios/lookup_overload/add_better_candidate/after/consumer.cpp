import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] auto result = pick(1);
  return static_cast<int>(result);
}
