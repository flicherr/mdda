export module Provider;

export namespace model {
struct X {};
long dispatch(X &value);
} // namespace model
export int dispatch(model::X const &value);
