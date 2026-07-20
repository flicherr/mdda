export module Provider;

export struct Item {};
export int inspect(...);
export template <class T, class = typename T::tag>
long inspect(T const &value) {
  return sizeof(value);
}
