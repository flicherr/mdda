export module Provider;

export struct Encodable {
  void encode() const;
};
export template <class T> int serialize(T const &value) {
  return sizeof(value);
}
