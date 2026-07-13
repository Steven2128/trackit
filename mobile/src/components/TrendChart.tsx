import { Dimensions } from "react-native";
import { BarChart } from "react-native-chart-kit";

import { colors } from "../theme/colors";

type Props = {
  months: string[];
  totals: number[];
};

const chartConfig = {
  backgroundGradientFrom: colors.surface,
  backgroundGradientTo: colors.surface,
  decimalPlaces: 0,
  color: (opacity = 1) => `rgba(91, 141, 239, ${opacity})`,
  labelColor: (opacity = 1) => `rgba(163, 168, 179, ${opacity})`,
  propsForBackgroundLines: { stroke: colors.border },
  barPercentage: 0.6,
  // BarChart only picks up formatYLabel from chartConfig (unlike LineChart's prop).
  formatYLabel: (raw: string) => compactCOP(raw),
};

const MES_ABREV = [
  "ene","feb","mar","abr","may","jun",
  "jul","ago","sep","oct","nov","dic",
];

function labelOf(yyyymm: string): string {
  const m = Number(yyyymm.split("-")[1]);
  return MES_ABREV[m - 1] ?? yyyymm;
}

// Raw COP values (7-8 digits) overflow the y-axis; compact them to $350k / $1,2M.
function compactCOP(raw: string): string {
  const n = Number(raw);
  if (!Number.isFinite(n) || n === 0) return "0";
  if (n >= 1_000_000) {
    const m = n / 1_000_000;
    return `$${(Math.round(m * 10) / 10).toString().replace(".", ",")}M`;
  }
  if (n >= 1_000) return `$${Math.round(n / 1_000)}k`;
  return `$${Math.round(n)}`;
}

export default function TrendChart({ months, totals }: Props) {
  const width = Dimensions.get("window").width - 32;
  return (
    <BarChart
      data={{
        labels: months.map(labelOf),
        datasets: [{ data: totals.length > 0 ? totals : [0] }],
      }}
      width={width}
      height={200}
      chartConfig={chartConfig}
      fromZero
      showValuesOnTopOfBars={false}
      withInnerLines
      yAxisLabel=""
      yAxisSuffix=""
      style={{ borderRadius: 12 }}
    />
  );
}
