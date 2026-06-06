import { customizeValidator } from "@rjsf/validator-ajv8";
import { RegistryFieldsType } from "@rjsf/utils";
import { ToolsField } from "./ToolsField";

// Shared RJSF validator
export const validator = customizeValidator({
    ajvOptionsOverrides: {
        removeAdditional: true,
    },
});

// Shared RJSF custom fields
export const fields: RegistryFieldsType = {
    ToolsField: ToolsField,
};

// Stable error logger for RJSF onError
export const onFormError = console.log.bind(console, "errors");

/**
 * Generate uiSchema from a JSON schema with custom x-* directives.
 * @param schema - The agent JSON schema
 * @param readOnlyFields - Field names to mark as read-only (e.g. ["id"] in edit mode)
 */
export function generateUiSchema(
    schema: Record<string, unknown> | undefined,
    readOnlyFields?: string[],
) {
    const uiSchema: Record<string, unknown> = {
        "ui:title": " ",
        "ui:description": " ",
    };

    if (schema && typeof schema.properties === "object" && schema.properties !== null) {
        const properties = schema.properties as Record<string, Record<string, unknown>>;
        const readOnlySet = new Set(readOnlyFields ?? []);

        Object.keys(properties).forEach((key) => {
            const property = properties[key];
            const uiProperty: Record<string, unknown> = {};

            if (key === "tools") {
                uiProperty["ui:field"] = "ToolsField";
            }

            if (readOnlySet.has(key)) {
                uiProperty["ui:readonly"] = true;
            }

            if (property["x-component"] === "category-select") {
                uiProperty["ui:widget"] = "ModelSelectWidget";
            }

            if (property["x-component"] === "picture-upload") {
                uiProperty["ui:widget"] = "PictureWidget";
            }

            if (typeof property["x-placeholder"] === "string") {
                uiProperty["ui:placeholder"] = property["x-placeholder"];
            }

            if (typeof property.maxLength === "number" && property.maxLength > 200) {
                uiProperty["ui:widget"] = "textarea";
            }

            if (property.type === "array" && (property.items as Record<string, unknown>)?.type === "string") {
                uiProperty["ui:widget"] = "StringArrayWidget";
            }

            if (Object.keys(uiProperty).length > 0) {
                uiSchema[key] = uiProperty;
            }
        });
    }

    return uiSchema;
}

/**
 * Filter validation errors: remove type errors for optional empty fields.
 */
export function createTransformErrors(
    formData: Record<string, unknown>,
    schema: Record<string, unknown> | undefined,
) {
    const requiredFields = (schema?.required as string[]) || [];

    return (errors: ReturnType<typeof validator.validateFormData>["errors"]) => {
        return errors.filter((error) => {
            const fieldName = error.property?.replace(/^\./, "").split(".")[0] || "";

            if (requiredFields.includes(fieldName)) {
                return true;
            }

            if (error.name === "type" || error.name === "enum") {
                const fieldValue = formData[fieldName];
                if (fieldValue === undefined || fieldValue === null || fieldValue === "") {
                    return false;
                }
            }

            return true;
        });
    };
}

/**
 * Clean up tools data before submission.
 * - Removes toolsets where enabled=false
 * - Removes tool states that are 'disabled'
 * - Optionally filters out tools/toolsets not in schema (for edit mode)
 */
export function cleanToolsData(
    data: Record<string, unknown>,
    schema?: Record<string, unknown>,
): Record<string, unknown> {
    const tools = data.tools as Record<string, { enabled?: boolean; states?: Record<string, string> }> | undefined;
    if (!tools) return data;

    const validCategories = getValidCategories(schema);

    const cleanedTools: Record<string, { enabled?: boolean; states?: Record<string, string> }> = {};
    for (const [categoryKey, categoryData] of Object.entries(tools)) {
        if (categoryData.enabled === false) continue;
        if (validCategories && !validCategories.has(categoryKey)) continue;

        const validTools = getValidToolsForToolset(schema, categoryKey);
        const states = categoryData.states || {};
        const cleanedStates: Record<string, string> = {};
        for (const [toolKey, toolValue] of Object.entries(states)) {
            if (toolValue === "disabled") continue;
            if (validTools && !validTools.has(toolKey)) continue;
            cleanedStates[toolKey] = toolValue;
        }

        if (categoryData.enabled === true) {
            cleanedTools[categoryKey] = {
                enabled: true,
                states: Object.keys(cleanedStates).length > 0 ? cleanedStates : undefined,
            };
        }
    }

    const restData = { ...data };
    delete (restData as Record<string, unknown>).autonomous;
    return {
        ...restData,
        tools: Object.keys(cleanedTools).length > 0 ? cleanedTools : undefined,
    };
}

/**
 * Filter agent data to only include fields defined in the schema.
 */
export function filterBySchema(
    agentData: Record<string, unknown>,
    schemaData: Record<string, unknown>,
): Record<string, unknown> {
    if (!schemaData.properties || typeof schemaData.properties !== "object") {
        return {};
    }
    const schemaProperties = schemaData.properties as Record<string, unknown>;
    const filtered: Record<string, unknown> = {};

    for (const key of Object.keys(schemaProperties)) {
        if (key in agentData) {
            filtered[key] = agentData[key];
        }
    }

    return filtered;
}

// --- Internal helpers ---

function getValidCategories(schema?: Record<string, unknown>): Set<string> | null {
    if (!schema?.properties) return null;
    const schemaProperties = schema.properties as Record<string, Record<string, unknown>>;
    const toolsSchema = schemaProperties.tools;
    if (!toolsSchema?.properties) return null;
    return new Set(Object.keys(toolsSchema.properties as Record<string, unknown>));
}

function getValidToolsForToolset(schema: Record<string, unknown> | undefined, categoryKey: string): Set<string> | null {
    if (!schema?.properties) return null;
    const schemaProperties = schema.properties as Record<string, Record<string, unknown>>;
    const toolsSchema = schemaProperties.tools;
    if (!toolsSchema?.properties) return null;
    const toolsetsSchema = toolsSchema.properties as Record<string, Record<string, unknown>>;
    const categorySchema = toolsetsSchema[categoryKey];
    if (!categorySchema?.properties) return null;
    const categoryProperties = categorySchema.properties as Record<string, Record<string, unknown>>;
    const statesSchema = categoryProperties.states;
    if (!statesSchema?.properties) return null;
    return new Set(Object.keys(statesSchema.properties as Record<string, unknown>));
}
