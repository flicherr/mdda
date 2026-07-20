export module Provider;

export namespace model {
struct X {};
long act(X value) { return sizeof(value); }
} // namespace model
export template <class T> int act(T const &value) { return sizeof(value); }
