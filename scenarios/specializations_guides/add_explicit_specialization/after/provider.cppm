export module Provider;

export template <class T> struct Value {
  static int make();
};
export template <> struct Value<int> {
  static long make();
};
