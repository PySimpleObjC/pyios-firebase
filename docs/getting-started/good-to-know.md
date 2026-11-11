# Good to know

- **Keep your listener.** Save the object that `add_snapshot_listener` gives back,
  and call `remove()` when you leave the screen. A listener keeps using the network
  and counts reads in your Firebase bill until you remove it.
- **Main thread.** If a callback changes widgets (for example, in Kivy) and you are
  not sure it runs on the main thread, use `Clock.schedule_once`:

  ```python
  from kivy.clock import Clock

  def on_cities(snapshot, error):
      Clock.schedule_once(lambda dt: update_screen(snapshot))
  ```
- **Blocks stay alive for you.** Every callback block is kept in memory until
  Firebase is done with it (listener blocks: until `remove()`). You do not need
  module-level variables.
- **Security rules.** If your Firestore rules need a signed-in user, call these
  methods only after sign-in works. Otherwise you get "permission denied".
- **Indexes.** Some queries need an index (many filters, or a filter plus an order
  on different fields, or collection group queries). The error message has a link
  to create it.
- **Reads cost money.** Reading a whole collection counts every document as a read.
  Use `query_limited_to` or an aggregate query when you can.
- **`update_data` needs an existing document.** To create it if it is missing, use
  `set_data`.
- **`set_data` replaces the whole document.** Old fields are lost, unless you pass
  `merge=True`.

