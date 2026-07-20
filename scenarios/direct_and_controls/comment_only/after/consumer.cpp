import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] auto result = compute(1);
  return result;
}
