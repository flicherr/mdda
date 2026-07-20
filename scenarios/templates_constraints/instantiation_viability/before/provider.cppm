export module Provider;

export struct Source {
  using value_type = int;
};
export template <class T> typename T::value_type produce();
