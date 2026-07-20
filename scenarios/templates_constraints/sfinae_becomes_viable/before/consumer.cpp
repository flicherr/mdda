import Provider;

int main() {
  Item value;
  [[clang::annotate("manalyzer_probe:result")]] auto result = inspect(value);
  return static_cast<int>(result);
}
