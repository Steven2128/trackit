import { StyleSheet, Text, TextProps } from "react-native";

import { colors } from "../theme/colors";
import { formatCOP } from "../utils/currency";

type Props = TextProps & {
  value: number | string | null | undefined;
  signed?: boolean;
  positive?: boolean;
  size?: "sm" | "md" | "lg" | "xl";
};

const SIZES: Record<NonNullable<Props["size"]>, number> = {
  sm: 12, md: 14, lg: 18, xl: 26,
};

export default function MoneyText({
  value, signed = false, positive = false, size = "md", style, ...rest
}: Props) {
  const text = formatCOP(value);
  const n = typeof value === "string" ? Number(value) : (value ?? 0);
  const withSign = signed && n > 0 ? `+${text}` : text;
  return (
    <Text
      {...rest}
      style={[
        styles.base,
        { fontSize: SIZES[size], color: positive ? colors.success : colors.textPrimary },
        style,
      ]}
    >
      {withSign}
    </Text>
  );
}

const styles = StyleSheet.create({
  base: { fontWeight: "700" },
});
