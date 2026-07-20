export module Provider;

export template <class T> struct Box {
  Box(T value);
};
export Box(long value) -> Box<int>;
