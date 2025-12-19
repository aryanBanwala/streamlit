const { createClient } = require("@supabase/supabase-js");
const fs = require("fs");
const path = require("path");

// Supabase config from env
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

const supabase = createClient(supabaseUrl, supabaseServiceKey);

// ============ CONFIG - EDIT THESE ============
const CONFIG = {
  // Input user IDs array (paste user_ids directly here)
  userIds: [
     "b6e3260c-2150-4b24-a249-ce48807fcc19",
    "43f1bb97-25bf-4835-97bf-4be3fd25224c",
    "3bd66fef-69bc-4a7d-948b-5beb49e6e463",
    "aba0d016-66ce-4d19-a766-a7b5f6780aa2",
    "b95560fb-9656-407a-bb3d-d0fe3a7914b3",
    "ab639a9b-b135-4a1a-81f9-6e3a45ee431b",
    "d497d5eb-2f31-4c07-8790-85c167c729e9",
    "54bdccc9-194b-4c31-ba55-fd7a725086a0",
    "d9e1b1ca-8698-4a04-8f79-751e0a851fd8",
    "310df72d-e20d-49a8-87a6-95ca4212c346",
    "a9219aa7-ea98-41fc-9d78-3083ec15f522",
    "fc57ff58-35da-4eaa-8780-c96d7ac0988f",
    "886abc3c-d975-4c1e-aefe-64f7310c2139",
    "07fed601-97fd-4526-b043-0965cbb4485b",
    "70373c77-3206-4588-b82e-e7ee56b75295",
    "d6f2b737-eeb9-4004-9b8f-75f21695b0b2",
    "d02da6c2-4eaa-4b15-8e12-d582ba45ce35",
    "ac025b09-a847-4702-a902-21be832a58da",
    "a4cfd0aa-1440-4ee9-9666-d17e9427d083",
    "87d4ce6a-8a75-4c2d-8409-cdedbc239fae",
    "3e31b454-342c-4981-b8e0-daef540f8112",
    "332768fb-3acb-4732-a83d-163cafc8d903",
    "12aafb17-ac94-4862-8dc3-ef037c048256",
    "a19cc99a-a0b7-4326-b869-43fa3c53ce10",
    "23b334ec-69dc-42cb-a24a-925465e492c2",
    "1de9d793-c3dc-4f5d-af5a-e7c6fc073b16",
    "46c883a3-e2a7-4ca6-8dc6-f0685ff8eaf3",
    "90bec849-8d62-416c-b3b3-8edf494474f6",
    "e5a90ea8-6b60-4dad-8e91-3ccaa6cd91db",
    "9f5decd1-28e6-4ebb-813a-1222cf53d40c",
    "2f7e7769-5899-46c3-bf63-9492ccce488f"
  ]
,

  // Email subject
  subject: "You have been shortlisted for a Christmas Date ✨",

  // Email body for MALE users (plain text, will be URL encoded)
  maleBody: `Hey,

This is Ishaan from Wavelength. We have a few recommendations for you for a Christmas date (some of them have liked you back too:p)

Have a look here: app.heywavelength.com/chat

Don't chase the "best" - shortlist the ones you feel might shortlist you back ✨

And if it's a match, we're treating you to an all-expense-paid date at Bastian on 25th December.

PS: Pls join our whatsapp community to receive notifs about upcoming recos: https://chat.whatsapp.com/LBFvmIadWAV2ugH6jOmIRd

Regards,
Team Wavelength`,

  // Email body for FEMALE users (plain text, will be URL encoded)
  femaleBody: `Hey,

This is Ishaan from Wavelength. We have a few recommendations for you for a Christmas date (some of them have liked you back too:p)

Have a look here: app.heywavelength.com/chat

Don't chase the "best" - shortlist the ones you feel might shortlist you back ✨

And if it's a match, we're treating you to an all-expense-paid date at Bastian on 25th December.

PS: Pls join our whatsapp community to receive notifs about upcoming recos: https://chat.whatsapp.com/KZfU52fVD0FBfwHhROV1rm

Regards,
Team Wavelength`,

  // Max emails per batch (Gmail URL has ~2000 char limit, ~20-30 emails is safe)
  batchSize: 25,

  // Test emails for spam checking (will be added as first batch with isTestBatch=true)
  testEmails: [
    "aryan@heywavelength.com",
    "jayanth@heywavelength.com",
    "vinit@heywavelength.com",
    "ishaan@heywavelength.com",
    "chetan@heywavelength.com",
  ],
};
// ============ END CONFIG ============

// URL char limit for Gmail compose URLs (keeping it safe)
const MAX_URL_LENGTH = 1800;

function generateGmailUrl(emails, subject, body) {
  const bccEmails = emails.join(",");
  const encodedSubject = encodeURIComponent(subject);
  const encodedBody = encodeURIComponent(body);

  return `https://mail.google.com/mail/u/0/?fs=1&bcc=${bccEmails}&su=${encodedSubject}&body=${encodedBody}&tf=cm`;
}

function batchEmails(emails, subject, body, maxBatchSize) {
  const batches = [];
  let currentBatch = [];

  for (const email of emails) {
    currentBatch.push(email);

    // Check if URL would be too long
    const testUrl = generateGmailUrl(currentBatch, subject, body);
    if (testUrl.length > MAX_URL_LENGTH || currentBatch.length >= maxBatchSize) {
      // If adding this email made it too long, remove it and save batch
      if (testUrl.length > MAX_URL_LENGTH) {
        currentBatch.pop();
        if (currentBatch.length > 0) {
          batches.push([...currentBatch]);
        }
        currentBatch = [email];
      } else {
        // Batch is full by count
        batches.push([...currentBatch]);
        currentBatch = [];
      }
    }
  }

  // Don't forget the last batch
  if (currentBatch.length > 0) {
    batches.push(currentBatch);
  }

  return batches;
}

async function generateEmailBatches() {
  const userIds = CONFIG.userIds.filter((id) => id && id.trim());

  console.log(`Processing ${userIds.length} user IDs from CONFIG`);

  if (userIds.length === 0) {
    console.log("No user IDs provided in CONFIG.userIds");
    console.log("Please add user IDs to the userIds array in CONFIG");
    process.exit(0);
  }

  // Fetch user details from Supabase (READ ONLY - just select)
  // Email is in user_data table, Gender is in user_metadata table
  console.log("Fetching user details from Supabase...");

  // Get emails from user_data
  const { data: userData, error: userDataError } = await supabase
    .from("user_data")
    .select("user_id, user_email")
    .in("user_id", userIds);

  if (userDataError) {
    console.error("Error fetching user_data:", userDataError);
    process.exit(1);
  }

  // Get gender from user_metadata
  const { data: userMetadata, error: userMetadataError } = await supabase
    .from("user_metadata")
    .select("user_id, gender")
    .in("user_id", userIds);

  if (userMetadataError) {
    console.error("Error fetching user_metadata:", userMetadataError);
    process.exit(1);
  }

  // Merge data - combine email from user_data and gender from user_metadata
  const users = userData.map((ud) => {
    const metadata = userMetadata.find((um) => um.user_id === ud.user_id);
    return {
      user_id: ud.user_id,
      user_email: ud.user_email,
      gender: metadata?.gender || null,
    };
  });

  console.log(`Fetched ${users.length} users from database`);
  console.log(`  - user_data records: ${userData.length}`);
  console.log(`  - user_metadata records: ${userMetadata.length}`);

  // Separate by gender
  const maleUsers = users.filter(
    (u) => u.gender?.toLowerCase() === "male" && u.user_email
  );
  const femaleUsers = users.filter(
    (u) => u.gender?.toLowerCase() === "female" && u.user_email
  );

  console.log(`Male users with email: ${maleUsers.length}`);
  console.log(`Female users with email: ${femaleUsers.length}`);

  // Generate batches
  const maleEmails = maleUsers.map((u) => u.user_email);
  const femaleEmails = femaleUsers.map((u) => u.user_email);

  const maleBatches = batchEmails(
    maleEmails,
    CONFIG.subject,
    CONFIG.maleBody,
    CONFIG.batchSize
  );
  const femaleBatches = batchEmails(
    femaleEmails,
    CONFIG.subject,
    CONFIG.femaleBody,
    CONFIG.batchSize
  );

  // Generate output
  const timestamp = new Date().toISOString().split("T")[0];

  // Generate test batch Gmail link
  const testGmailLinkMale = generateGmailUrl(CONFIG.testEmails, CONFIG.subject, CONFIG.maleBody);
  const testGmailLinkFemale = generateGmailUrl(CONFIG.testEmails, CONFIG.subject, CONFIG.femaleBody);

  // Male CSV
  const maleCsvPath = path.join(
    __dirname,
    "utils",
    `generated__from_user_ids_male_email_batches_${timestamp}.csv`
  );
  let maleCsvContent = "batch_number,email_count,isTestBatch,user_ids,emails,gmail_link\n";

  // Add test batch first (batch 0)
  maleCsvContent += `0,${CONFIG.testEmails.length},true,"test_users","${CONFIG.testEmails.join(";")}","${testGmailLinkMale}"\n`;

  maleBatches.forEach((batch, index) => {
    const batchUserIds = maleUsers
      .filter((u) => batch.includes(u.user_email))
      .map((u) => u.user_id)
      .join(";");
    const batchEmails = batch.join(";");
    const gmailLink = generateGmailUrl(batch, CONFIG.subject, CONFIG.maleBody);
    maleCsvContent += `${index + 1},${batch.length},false,"${batchUserIds}","${batchEmails}","${gmailLink}"\n`;
  });

  fs.writeFileSync(maleCsvPath, maleCsvContent);
  console.log(`\nMale batches CSV saved: ${maleCsvPath}`);
  console.log(`  Test batch: 1 (${CONFIG.testEmails.length} emails)`);
  console.log(`  User batches: ${maleBatches.length}`);
  console.log(`  Total user emails: ${maleEmails.length}`);

  // Female CSV
  const femaleCsvPath = path.join(
    __dirname,
    "utils",
    `generated__from_user_ids_female_email_batches_${timestamp}.csv`
  );
  let femaleCsvContent = "batch_number,email_count,isTestBatch,user_ids,emails,gmail_link\n";

  // Add test batch first (batch 0)
  femaleCsvContent += `0,${CONFIG.testEmails.length},true,"test_users","${CONFIG.testEmails.join(";")}","${testGmailLinkFemale}"\n`;

  femaleBatches.forEach((batch, index) => {
    const batchUserIds = femaleUsers
      .filter((u) => batch.includes(u.user_email))
      .map((u) => u.user_id)
      .join(";");
    const batchEmails = batch.join(";");
    const gmailLink = generateGmailUrl(
      batch,
      CONFIG.subject,
      CONFIG.femaleBody
    );
    femaleCsvContent += `${index + 1},${batch.length},false,"${batchUserIds}","${batchEmails}","${gmailLink}"\n`;
  });

  fs.writeFileSync(femaleCsvPath, femaleCsvContent);
  console.log(`\nFemale batches CSV saved: ${femaleCsvPath}`);
  console.log(`  Test batch: 1 (${CONFIG.testEmails.length} emails)`);
  console.log(`  User batches: ${femaleBatches.length}`);
  console.log(`  Total user emails: ${femaleEmails.length}`);

  // Summary
  console.log("\n========== SUMMARY ==========");
  console.log(`Total users processed: ${users.length}`);
  console.log(`Male: ${maleUsers.length} users in ${maleBatches.length} batches`);
  console.log(`Female: ${femaleUsers.length} users in ${femaleBatches.length} batches`);
  console.log(`Users without email: ${users.filter((u) => !u.user_email).length}`);
  console.log(`Users without gender: ${users.filter((u) => !u.gender).length}`);
}

generateEmailBatches().catch(console.error);