export module Provider;

export struct Four {
  char bytes[4];
};
export template <class T>
concept AnyType = true;
export template <class T>
concept FourByte = AnyType<T> && (sizeof(T) == 4);
export template <class T>
  requires AnyType<T>
int order(T *value) {
  return sizeof(*value);
}
export template <class T>
  requires FourByte<T>
long order(T *value) {
  return sizeof(*value);
}
