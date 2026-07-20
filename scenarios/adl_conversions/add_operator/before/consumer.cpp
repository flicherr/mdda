import Provider;

int main() {
  model::X value;
  [[clang::annotate("manalyzer_probe:result")]] auto result = value + 1;
  return static_cast<int>(result);
}
