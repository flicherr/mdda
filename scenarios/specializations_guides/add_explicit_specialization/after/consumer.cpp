import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] auto result = Value<int>::make();
  return static_cast<int>(result);
}
