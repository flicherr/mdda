export module Provider;

export template <class T> int choose(T value) { return sizeof(value); }
export long choose(int value) { return value; }
