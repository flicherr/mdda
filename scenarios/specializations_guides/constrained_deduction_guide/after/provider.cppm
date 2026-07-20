export module Provider;

export template <class T> struct Holder {
  Holder(T value);
};
export template <class T> Holder(T value) -> Holder<T>;
export template <class T>
  requires(sizeof(T) == 1)
Holder(T value) -> Holder<int>;
