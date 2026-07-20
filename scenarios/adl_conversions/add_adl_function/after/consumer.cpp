import Provider;

int main() {
  model::X value;
  [[clang::annotate("manalyzer_probe:result")]] auto result = act(value);
  return static_cast<int>(result);
}
