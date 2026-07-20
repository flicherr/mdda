import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] auto result = Box<int *>::make();
  return static_cast<int>(result);
}
