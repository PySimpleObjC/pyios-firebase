// Callable functions for the iOS e2e suite (e2e/ios/src/functions_tests.py).
// They only run in the Functions emulator, for the offline demo project.
const { onCall, HttpsError } = require("firebase-functions/v2/https");

// returns what it gets, so the test can compare types both ways
exports.echo = onCall((request) => ({ data: request.data }));

// an HttpsError with details: the client gets the code, message and details
exports.fail = onCall((request) => {
  throw new HttpsError("invalid-argument", "bad input", { field: "text", hint: request.data });
});

// an unexpected error: the client gets INTERNAL, without the message
exports.crash = onCall(() => {
  throw new Error("secret server detail");
});

// sleeps, for the timeout test
exports.slow = onCall(async (request) => {
  await new Promise((resolve) => setTimeout(resolve, request.data.ms));
  return "done";
});

// the Auth user the emulator verified from the ID token the SDK sent
exports.whoAmI = onCall((request) => ({ uid: request.auth ? request.auth.uid : null }));

// the App Check token the SDK sent (the emulator does not verify it)
exports.appCheckToken = onCall((request) => ({
  header: request.rawRequest.header("X-Firebase-AppCheck") || null,
}));

// a function in another region
exports.regional = onCall({ region: "europe-west1" }, () => ({ region: "europe-west1" }));
