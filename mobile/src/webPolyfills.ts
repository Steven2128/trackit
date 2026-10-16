import { Platform, TextInput } from "react-native";

// @gorhom/bottom-sheet's BottomSheetTextInput calls
// `TextInput.State.currentlyFocusedInput()` on blur; react-native-web only
// ships the older `currentlyFocusedField()`. Alias it so blurring a sheet
// input doesn't throw in the browser.
if (Platform.OS === "web") {
  const state = TextInput.State as typeof TextInput.State & {
    currentlyFocusedField?: () => unknown;
  };
  if (!state.currentlyFocusedInput && state.currentlyFocusedField) {
    (state as { currentlyFocusedInput: () => unknown }).currentlyFocusedInput =
      state.currentlyFocusedField.bind(state);
  }
}
