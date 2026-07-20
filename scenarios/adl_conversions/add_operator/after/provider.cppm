export module Provider;

export namespace model {
struct X {
  operator int() const;
};
long operator+(X value, int offset);
} // namespace model
