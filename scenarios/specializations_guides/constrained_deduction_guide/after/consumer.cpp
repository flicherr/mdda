import Provider;

int main() {
  char value = 0;
  [[clang::annotate("manalyzer_probe:result")]] Holder result(value);
  return 0;
}
