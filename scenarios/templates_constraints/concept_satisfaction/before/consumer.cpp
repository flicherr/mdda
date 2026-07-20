import Provider;

int main() {
  [[clang::annotate("manalyzer_probe:result")]] constexpr bool result = Fits<Wide>;
  return result ? 0 : 1;
}
