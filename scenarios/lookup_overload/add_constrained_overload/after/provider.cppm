export module Provider;

export template <class T> int rank(T value) { return sizeof(value); }
export template <class T>
  requires(sizeof(T) == 4)
long rank(T value) {
  return sizeof(value);
}
