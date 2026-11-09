import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useContacts, useCreateContact } from "../services/queries/contacts";
import { colors } from "../theme/colors";
import { Alert } from "../utils/alert";
import { BottomSheetTextInput } from "./sheet";

type Props = {
  value: string | null;
  onChange: (id: string | null) => void;
  // Offer "Nadie" (unassign); off when a person is required.
  allowNone?: boolean;
};

/** Chips with the user's contacts plus "+ Nueva" to add one inline. Lives
 * inside bottom sheets, hence BottomSheetTextInput. */
export default function ContactPicker({ value, onChange, allowNone = true }: Props) {
  const { data: contacts } = useContacts();
  const create = useCreateContact();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");

  function save() {
    const clean = name.trim();
    if (!clean || create.isPending) return;
    create.mutate(clean, {
      onSuccess: (c) => {
        onChange(c.id);
        setName("");
        setAdding(false);
      },
      onError: (e) =>
        Alert.alert(
          "No se pudo crear",
          (e as { response?: { status?: number } }).response?.status === 409
            ? "Ya tenés a alguien con ese nombre."
            : e instanceof Error
              ? e.message
              : "Probá de nuevo.",
        ),
    });
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.chips}>
        {allowNone ? (
          <Chip label="Nadie" active={value === null} onPress={() => onChange(null)} />
        ) : null}
        {(contacts ?? []).map((c) => (
          <Chip key={c.id} label={c.name} active={value === c.id} onPress={() => onChange(c.id)} />
        ))}
        {!adding ? <Chip label="+ Nueva" active={false} onPress={() => setAdding(true)} /> : null}
      </View>
      {adding ? (
        <View style={styles.addRow}>
          <BottomSheetTextInput
            style={styles.input}
            placeholder="Nombre (ej: Jesús)"
            placeholderTextColor={colors.textSecondary}
            value={name}
            onChangeText={setName}
            maxLength={64}
            autoFocus
            onSubmitEditing={save}
          />
          <Pressable style={styles.addBtn} onPress={save} disabled={create.isPending}>
            <Text style={styles.addText}>{create.isPending ? "..." : "Crear"}</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.chip, active && styles.chipActive]}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 8 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: colors.surface,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textSecondary, fontSize: 12, fontWeight: "600" },
  chipTextActive: { color: "#fff" },
  addRow: { flexDirection: "row", gap: 8, alignItems: "center" },
  input: {
    flex: 1,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 10,
    fontSize: 14,
    color: colors.textPrimary,
  },
  addBtn: {
    backgroundColor: colors.primary,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  addText: { color: "#fff", fontWeight: "600", fontSize: 13 },
});
