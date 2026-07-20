export module Provider;

export namespace model {
struct X {
  friend long touch(X value) { return sizeof(value); }
};
} // namespace model
export template <class T> int touch(T const &value) { return sizeof(value); }
