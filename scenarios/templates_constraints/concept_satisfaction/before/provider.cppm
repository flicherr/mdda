export module Provider;

export struct Wide {
  char bytes[8];
};
export template <class T>
concept Fits = (sizeof(T) <= 4);
