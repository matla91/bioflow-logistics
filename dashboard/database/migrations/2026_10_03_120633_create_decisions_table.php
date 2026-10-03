<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('decisions', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('shipment_id')->constrained()->cascadeOnDelete();
            $table->foreignId('assessment_id')->unique()->constrained()->cascadeOnDelete();
            $table->foreignId('user_id')->constrained();
            $table->string('role');
            $table->string('verdict');
            $table->string('action');
            $table->text('reason');
            $table->char('snapshot_sha256', 64);
            $table->timestamp('decided_at');
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('decisions');
    }
};
