import { StyleSheet, Text, View } from "react-native";

import { colors } from "../theme/colors";
import { getCategory } from "../utils/categories";

type Props = {
  categoryKey: string | null | undefined;
  size?: number;
};

export default function CategoryIcon({ categoryKey, size = 36 }: Props) {
  const cat = getCategory(categoryKey);
  return (
    <View style={[styles.wrap, { width: size, height: size, borderRadius: size / 2 }]}>
      <Text style={{ fontSize: size * 0.5 }}>{cat.emoji}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
});
