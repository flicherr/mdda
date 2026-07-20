export module Provider;

export namespace detail {
int route(long value);
long route(int value);
} // namespace detail
export using detail::route;
