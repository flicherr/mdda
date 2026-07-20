import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] auto result = used(1);
  return result;
}
