import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] Box result(1L);
  return 0;
}
