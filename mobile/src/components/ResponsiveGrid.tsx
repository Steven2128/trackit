import { Children, type ReactNode } from "react";
import { StyleSheet, View } from "react-native";

import { useIsWide } from "../theme/layout";

type Props = {
  children: ReactNode;
  /** Columns on wide screens; phones always get a single column. */
  columns?: number;
  gap?: number;
};

/**
 * Lays its children out in `columns` equal columns on wide screens and
 * leaves them untouched (stacked, as designed for the phone) otherwise.
 * Children keep their own vertical margins.
 */
export default function ResponsiveGrid({ children, columns = 2, gap = 12 }: Props) {
  const isWide = useIsWide();
  if (!isWide || columns <= 1) return <>{children}</>;

  return (
    <View style={[styles.grid, { marginHorizontal: -gap / 2 }]}>
      {Children.toArray(children).map((child, i) => (
        <View key={i} style={{ width: `${100 / columns}%`, paddingHorizontal: gap / 2 }}>
          {child}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: "row", flexWrap: "wrap" },
});
