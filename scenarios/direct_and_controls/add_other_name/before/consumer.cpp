import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] auto result = target(1);
  return result;
}
