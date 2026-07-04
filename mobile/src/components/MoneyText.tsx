import { StyleSheet, Text, TextProps } from "react-native";

import { colors } from "../theme/colors";
import { formatCOP } from "../utils/currency";

type Props = TextProps & {
  value: number | string | null | undefined;
  signed?: boolean;
  positive?: boolean;
  negative?: boolean;
  size?: "sm" | "md" | "lg" | "xl";
};

const SIZES: Record<NonNullable<Props["size"]>, number> = {
  sm: 12, md: 14, lg: 18, xl: 26,
};

export default function MoneyText({
  value, signed = false, positive = false, negative = false, size = "md", style, ...rest
}: Props) {
  const text = formatCOP(value);
  const n = typeof value === "string" ? Number(value) : (value ?? 0);
  const prefix = negative ? "-" : signed && n > 0 ? "+" : "";
  const color = negative
    ? colors.danger
    : positive
      ? colors.success
      : colors.textPrimary;
  return (
    <Text
      {...rest}
      style={[styles.base, { fontSize: SIZES[size], color }, style]}
    >
      {`${prefix}${text}`}
    </Text>
  );
}

const styles = StyleSheet.create({
  base: { fontWeight: "700" },
});
