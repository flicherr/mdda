import Provider;

int main() {
  model::X value;
  [[clang::annotate("manalyzer_probe:result")]] auto result = touch(value);
  return static_cast<int>(result);
}
