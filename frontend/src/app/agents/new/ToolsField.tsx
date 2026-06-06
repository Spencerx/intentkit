"use client";
import React from "react";
import { FieldProps } from "@rjsf/utils";
import { ToolsetCard } from "./ToolsetCard";
import { config } from "@/lib/config";

interface ToolsetSchema {
    title?: string;
    description?: string;
    "x-icon"?: string;
    properties?: {
        enabled?: {
            default?: boolean;
        };
        states?: {
            properties?: Record<string, {
                title?: string;
                description?: string;
                enum?: string[];
                "x-enum-title"?: string[];
                default?: string;
            }>;
        };
    };
}

interface ToolsFormData {
    [toolset: string]: {
        enabled?: boolean;
        states?: Record<string, string>;
    };
}

/**
 * Custom field for rendering the entire tools object.
 * Each toolset is rendered as a collapsible card.
 */
export function ToolsField(props: FieldProps<ToolsFormData>) {
    const { schema, formData, onChange, idSchema, fieldPathId } = props;

    const toolsets = (schema.properties || {}) as Record<string, ToolsetSchema>;
    const currentFormData = (formData || {}) as ToolsFormData;

    const handleCategoryEnabledChange = (categoryKey: string, enabled: boolean) => {
        const newFormData = {
            ...currentFormData,
            [categoryKey]: {
                ...currentFormData[categoryKey],
                enabled,
            },
        };
        onChange(newFormData, fieldPathId.path);
    };

    const handleToolStateChange = (
        categoryKey: string,
        toolKey: string,
        value: string
    ) => {
        const categoryData = currentFormData[categoryKey] || {};
        const currentStates = categoryData.states || {};

        if (value === "disabled") {
            // When disabling, remove the tool from states using object filter
            const restStates = Object.fromEntries(
                Object.entries(currentStates).filter(([key]) => key !== toolKey)
            );
            const newFormData = {
                ...currentFormData,
                [categoryKey]: {
                    ...categoryData,
                    states: restStates,
                },
            };
            // RJSF v6 onChange signature: (newValue, path, errorSchema?, id?)
            onChange(newFormData, fieldPathId.path);
        } else {
            // When enabling (private), add the tool to states
            const newFormData = {
                ...currentFormData,
                [categoryKey]: {
                    ...categoryData,
                    states: {
                        ...currentStates,
                        [toolKey]: value,
                    },
                },
            };
            // RJSF v6 onChange signature: (newValue, path, errorSchema?, id?)
            onChange(newFormData, fieldPathId.path);
        }
    };

    // Sort toolsets alphabetically by title
    const sortedCategories = Object.entries(toolsets).sort(([, a], [, b]) => {
        const titleA = a.title || "";
        const titleB = b.title || "";
        return titleA.localeCompare(titleB);
    });

    return (
        <div id={idSchema?.$id || "tools-field"} className="space-y-4">
            {/* Tools section header */}
            <div className="mb-2">
                {schema.title && (
                    <label className="block text-base font-bold mb-1">{schema.title}</label>
                )}
                {schema.description && (
                    <p className="text-xs font-normal text-muted-foreground">{schema.description}</p>
                )}
            </div>
            {sortedCategories.map(([categoryKey, categorySchema]) => {
                const categoryData = currentFormData[categoryKey] || {};
                const enabled = categoryData.enabled ?? (categorySchema.properties?.enabled?.default || false);
                const statesSchema = categorySchema.properties?.states?.properties || {};
                const statesData = categoryData.states || {};

                // Build tool state configs from schema
                const toolStates = Object.entries(statesSchema).map(([toolKey, toolSchema]) => {
                    const enumValues = toolSchema.enum || ["disabled", "public", "private"];
                    const enumTitles = toolSchema["x-enum-title"] || enumValues;

                    return {
                        title: toolSchema.title || toolKey,
                        description: toolSchema.description,
                        value: statesData[toolKey] ?? (toolSchema.default || "disabled"),
                        options: enumValues.map((val, idx) => ({
                            value: val,
                            label: enumTitles[idx] || val,
                        })),
                        onChange: (value: string) =>
                            handleToolStateChange(categoryKey, toolKey, value),
                    };
                });

                // Build icon URL: relative paths get API base prefix, absolute URLs pass through
                const rawIcon = categorySchema["x-icon"];
                const iconUrl = rawIcon
                    ? rawIcon.startsWith("/")
                        ? `${config.apiBaseUrl}${rawIcon}`
                        : rawIcon
                    : undefined;

                return (
                    <ToolsetCard
                        key={categoryKey}
                        title={categorySchema.title || categoryKey}
                        description={categorySchema.description}
                        iconUrl={iconUrl}
                        enabled={enabled}
                        onEnabledChange={(e) => handleCategoryEnabledChange(categoryKey, e)}
                        toolStates={toolStates}
                    />
                );
            })}
        </div>
    );
}
