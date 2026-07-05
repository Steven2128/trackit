import { Ionicons } from "@expo/vector-icons";
import { StyleSheet, View } from "react-native";

import { getCategory } from "../utils/categories";

type Props = {
  categoryKey: string | null | undefined;
  size?: number;
};

export default function CategoryIcon({ categoryKey, size = 36 }: Props) {
  const cat = getCategory(categoryKey);
  return (
    <View
      accessibilityLabel={cat.label}
      style={[
        styles.wrap,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          // 15% alpha tint of the category color keeps icons legible on dark surfaces
          backgroundColor: `${cat.color}26`,
        },
      ]}
    >
      <Ionicons name={cat.icon} size={size * 0.5} color={cat.color} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: "center",
    justifyContent: "center",
  },
});
