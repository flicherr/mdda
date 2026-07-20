import Provider;

int main() {
  Encodable value;
  [[clang::annotate("manalyzer_probe:result")]] auto result = serialize(value);
  return static_cast<int>(result);
}
