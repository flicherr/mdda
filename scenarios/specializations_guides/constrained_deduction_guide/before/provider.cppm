export module Provider;

export template <class T> struct Holder {
  Holder(T value);
};
export template <class T> Holder(T value) -> Holder<T>;
