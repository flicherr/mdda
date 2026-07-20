import Provider;

int main() {
  Four value{};
  [[clang::annotate("manalyzer_probe:result")]] auto result = order(&value);
  return static_cast<int>(result);
}
