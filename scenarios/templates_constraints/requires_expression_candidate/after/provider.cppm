export module Provider;

export struct Encodable {
  void encode() const;
};
export template <class T> int serialize(T const &value) {
  return sizeof(value);
}
export template <class T>
  requires requires(T const &value) { value.encode(); }
long serialize(T const &value) {
  return sizeof(value);
}
