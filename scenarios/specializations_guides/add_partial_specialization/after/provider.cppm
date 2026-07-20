export module Provider;

export template <class T> struct Box {
  static int make();
};
export template <class T> struct Box<T *> {
  static long make();
};
