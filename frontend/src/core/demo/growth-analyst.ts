const EXPERIMENT_ROW_COUNT = 200;

export const GROWTH_ANALYST_DEMO_SCENARIO_IDS = [
  "experiment",
  "channel",
  "retention",
  "product",
] as const;

export type GrowthAnalystDemoScenarioId =
  (typeof GROWTH_ANALYST_DEMO_SCENARIO_IDS)[number];

export type GrowthAnalystDemoScenario = {
  id: GrowthAnalystDemoScenarioId;
  files: readonly string[];
  createFiles: () => File[];
};

const generatedDemoFiles = new WeakSet<File>();

function csvFile(name: string, rows: string[]) {
  const file = new File([`${rows.join("\n")}\n`], name, {
    type: "text/csv",
  });
  generatedDemoFiles.add(file);
  return file;
}

function isoDate(baseDate: string, offsetDays: number) {
  const date = new Date(`${baseDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

function createExperimentFiles(): File[] {
  const customers = ["user_id,segment,signup_date,channel"];
  const assignments = ["user_id,variant,assigned_at"];
  const outcomes = ["user_id,converted,order_value,converted_at"];

  for (let index = 1; index <= EXPERIMENT_ROW_COUNT; index += 1) {
    const userId = `user-${String(index).padStart(3, "0")}`;
    const variant = index <= EXPERIMENT_ROW_COUNT / 2 ? "control" : "variant";
    const signupDay = String(((index - 1) % 28) + 1).padStart(2, "0");
    const converted = index <= 10 || (index >= 101 && index <= 120) ? 1 : 0;
    const orderValue = converted ? (index % 3 === 0 ? 129 : 99) : 0;

    customers.push(`${userId},new,2026-07-${signupDay},organic`);
    assignments.push(`${userId},${variant},2026-08-01`);
    outcomes.push(
      `${userId},${converted},${orderValue},${converted ? "2026-08-05" : ""}`,
    );
  }

  return [
    csvFile("customers.csv", customers),
    csvFile("assignments.csv", assignments),
    csvFile("outcomes.csv", outcomes),
  ];
}

function createChannelFiles(): File[] {
  const adSpend = ["date,channel,campaign,spend,impressions,clicks"];
  const sessions = [
    "date,channel,campaign,sessions,product_views,add_to_cart",
  ];
  const orders = ["date,channel,campaign,orders,revenue,refund_amount"];
  const channelProfiles = [
    {
      channel: "xiaohongshu",
      spend: 3000,
      impressions: 90000,
      clicks: 3600,
      sessions: 3200,
      productViews: 2600,
      addToCart: 520,
      orders: 80,
    },
    {
      channel: "douyin",
      spend: 2800,
      impressions: 150000,
      clicks: 2700,
      sessions: 2350,
      productViews: 1800,
      addToCart: 310,
      orders: 42,
    },
    {
      channel: "search",
      spend: 1600,
      impressions: 45000,
      clicks: 1850,
      sessions: 1700,
      productViews: 1400,
      addToCart: 260,
      orders: 34,
    },
    {
      channel: "display",
      spend: 1700,
      impressions: 210000,
      clicks: 1250,
      sessions: 980,
      productViews: 650,
      addToCart: 105,
      orders: 12,
    },
  ];

  for (let day = 0; day < 30; day += 1) {
    const date = isoDate("2026-07-01", day);
    const variation = (day % 3) - 1;

    for (const profile of channelProfiles) {
      const campaign = `${profile.channel}-campaign-${(day % 3) + 1}`;
      const spend = profile.spend + variation * 50;
      const impressions = profile.impressions + variation * 1000;
      const clicks = profile.clicks + variation * 40;
      const sessionCount = profile.sessions + variation * 35;
      const productViews = profile.productViews + variation * 30;
      const addToCart = profile.addToCart + variation * 8;
      const orderCount = profile.orders + variation * 2;
      const revenue = orderCount * 139;
      const refundAmount = day % 10 === 9 ? 139 : 0;

      adSpend.push(
        `${date},${profile.channel},${campaign},${spend},${impressions},${clicks}`,
      );
      sessions.push(
        `${date},${profile.channel},${campaign},${sessionCount},${productViews},${addToCart}`,
      );
      orders.push(
        `${date},${profile.channel},${campaign},${orderCount},${revenue},${refundAmount}`,
      );
    }
  }

  return [
    csvFile("ad_spend.csv", adSpend),
    csvFile("sessions.csv", sessions),
    csvFile("orders.csv", orders),
  ];
}

function createRetentionFiles(): File[] {
  const users = ["user_id,signup_date,cohort_week,acquisition_channel,city"];
  const events = ["user_id,event_date,event_name"];
  const subscriptions = [
    "user_id,plan,start_date,status,monthly_fee",
  ];
  const channelProfiles = [
    { channel: "referral", d1: 4, d7: 3, d30: 2 },
    { channel: "organic", d1: 3, d7: 2, d30: 1 },
    { channel: "xiaohongshu", d1: 3, d7: 2, d30: 1 },
    { channel: "paid_display", d1: 2, d7: 1, d30: 0 },
  ];
  let userIndex = 0;

  for (let cohort = 0; cohort < 12; cohort += 1) {
    const signupDate = isoDate("2026-04-06", cohort * 7);

    for (const profile of channelProfiles) {
      for (let position = 1; position <= 5; position += 1) {
        userIndex += 1;
        const userId = `cohort-user-${String(userIndex).padStart(3, "0")}`;
        const city = userIndex % 2 === 0 ? "Shanghai" : "Shenzhen";

        users.push(
          `${userId},${signupDate},${signupDate},${profile.channel},${city}`,
        );
        events.push(`${userId},${signupDate},signup`);
        if (position <= profile.d1) {
          events.push(`${userId},${isoDate(signupDate, 1)},active_session`);
        }
        if (position <= profile.d7) {
          events.push(`${userId},${isoDate(signupDate, 7)},active_session`);
          events.push(`${userId},${isoDate(signupDate, 7)},product_view`);
        }
        if (position <= profile.d30) {
          events.push(`${userId},${isoDate(signupDate, 30)},active_session`);
          events.push(`${userId},${isoDate(signupDate, 30)},purchase`);
        }

        if (position <= profile.d30) {
          subscriptions.push(
            `${userId},monthly,${isoDate(signupDate, 7)},active,39`,
          );
        } else if (position <= profile.d7) {
          subscriptions.push(
            `${userId},monthly,${isoDate(signupDate, 7)},churned,39`,
          );
        } else {
          subscriptions.push(`${userId},none,,none,0`);
        }
      }
    }
  }

  return [
    csvFile("users.csv", users),
    csvFile("events.csv", events),
    csvFile("subscriptions.csv", subscriptions),
  ];
}

function createProductFiles(): File[] {
  const products = [
    "product_id,product_name,category,price,cost,inventory_on_hand",
  ];
  const orders = ["order_id,user_id,order_date,channel,status"];
  const orderItems = [
    "order_id,product_id,quantity,unit_price,unit_cost,discount",
  ];
  const productProfiles = [
    {
      id: "sku-001",
      name: "Commuter Tumbler",
      category: "drinkware",
      price: 139,
      cost: 78,
      inventory: 84,
      units: 72,
    },
    {
      id: "sku-002",
      name: "Premium Travel Mug",
      category: "drinkware",
      price: 199,
      cost: 82,
      inventory: 46,
      units: 18,
    },
    {
      id: "sku-003",
      name: "Straw Cup",
      category: "drinkware",
      price: 119,
      cost: 47,
      inventory: 72,
      units: 45,
    },
    {
      id: "sku-004",
      name: "Cleaning Kit",
      category: "accessory",
      price: 39,
      cost: 12,
      inventory: 110,
      units: 30,
    },
    {
      id: "sku-005",
      name: "Gift Set",
      category: "bundle",
      price: 259,
      cost: 136,
      inventory: 38,
      units: 12,
    },
    {
      id: "sku-006",
      name: "Replacement Lid",
      category: "accessory",
      price: 29,
      cost: 6,
      inventory: 150,
      units: 40,
    },
    {
      id: "sku-007",
      name: "Mini Bottle",
      category: "drinkware",
      price: 99,
      cost: 51,
      inventory: 95,
      units: 20,
    },
    {
      id: "sku-008",
      name: "Legacy Cup",
      category: "drinkware",
      price: 109,
      cost: 66,
      inventory: 180,
      units: 3,
    },
  ];
  const channels = ["xiaohongshu", "douyin", "search", "direct"];
  let orderIndex = 0;

  for (const product of productProfiles) {
    products.push(
      `${product.id},${product.name},${product.category},${product.price},${product.cost},${product.inventory}`,
    );

    for (let unit = 0; unit < product.units; unit += 1) {
      orderIndex += 1;
      const orderId = `order-${String(orderIndex).padStart(3, "0")}`;
      const userId = `buyer-${String(((orderIndex - 1) % 120) + 1).padStart(3, "0")}`;
      const orderDate = isoDate("2026-07-01", (orderIndex - 1) % 30);
      const channel = channels[(orderIndex - 1) % channels.length];
      const status = orderIndex % 37 === 0 ? "refunded" : "completed";
      const discount = orderIndex % 5 === 0 ? 10 : 0;

      orders.push(`${orderId},${userId},${orderDate},${channel},${status}`);
      orderItems.push(
        `${orderId},${product.id},1,${product.price},${product.cost},${discount}`,
      );
    }
  }

  return [
    csvFile("products.csv", products),
    csvFile("orders.csv", orders),
    csvFile("order_items.csv", orderItems),
  ];
}

export const GROWTH_ANALYST_DEMO_SCENARIOS: Record<
  GrowthAnalystDemoScenarioId,
  GrowthAnalystDemoScenario
> = {
  experiment: {
    id: "experiment",
    files: ["customers.csv", "assignments.csv", "outcomes.csv"],
    createFiles: createExperimentFiles,
  },
  channel: {
    id: "channel",
    files: ["ad_spend.csv", "sessions.csv", "orders.csv"],
    createFiles: createChannelFiles,
  },
  retention: {
    id: "retention",
    files: ["users.csv", "events.csv", "subscriptions.csv"],
    createFiles: createRetentionFiles,
  },
  product: {
    id: "product",
    files: ["products.csv", "orders.csv", "order_items.csv"],
    createFiles: createProductFiles,
  },
};

export const GROWTH_ANALYST_DEMO_FILES =
  GROWTH_ANALYST_DEMO_SCENARIOS.experiment.files;

export const ALL_GROWTH_ANALYST_DEMO_FILES = Array.from(
  new Set(
    GROWTH_ANALYST_DEMO_SCENARIO_IDS.flatMap(
      (scenarioId) => GROWTH_ANALYST_DEMO_SCENARIOS[scenarioId].files,
    ),
  ),
);

export function createGrowthAnalystDemoFiles(
  scenarioId: GrowthAnalystDemoScenarioId = "experiment",
): File[] {
  return GROWTH_ANALYST_DEMO_SCENARIOS[scenarioId].createFiles();
}

export function isGrowthAnalystDemoFile(file: File | undefined): boolean {
  return file instanceof File && generatedDemoFiles.has(file);
}
